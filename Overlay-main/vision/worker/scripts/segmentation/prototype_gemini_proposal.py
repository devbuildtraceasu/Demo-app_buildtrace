import base64
import json
import os
import sys

import cv2
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Add worker root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from dotenv import load_dotenv

# Load .env from worker root
worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
load_dotenv(os.path.join(worker_root, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3-pro-preview"

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment.")
    sys.exit(1)


class BoundingBox(BaseModel):
    label: str = Field(
        description="Type of region: 'plan', 'elevation', 'section', 'detail', 'schedule', 'title_block', 'consultants', 'seals', 'revision_history', 'notes', 'legend'"
    )
    ymin: int = Field(description="Top Y coordinate (0-1000)")
    xmin: int = Field(description="Left X coordinate (0-1000)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000)")
    xmax: int = Field(description="Right X coordinate (0-1000)")
    description: str = Field(description="Brief description of the content")


class SegmentationProposal(BaseModel):
    regions: list[BoundingBox] = Field(description="List of proposed bounding boxes")


SYSTEM_PROMPT = """You are an expert architectural document analyzer.
Your task is to identify and segment the distinct "blocks" of information on a construction drawing sheet.
Common blocks include:
- Individual Floor Plans, Elevations, or Sections
- Schedules (tables of data)
- Detail views
- Title Blocks
- General Notes
- Key Notes
- Key Plan
- Consultants
- Seals
- Revision History
- Legends

For each block, estimate a bounding box that encompasses the entire content of that block.
Be sure to separate blocks that are distinct rectangular boxes.
IMPORTANT: Return coordinates normalized to a 1000x1000 grid (0-1000).
ymin, xmin, ymax, xmax."""


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def propose_regions_gemini(image_path: str, output_path: str):
    print(f"Processing {image_path} with Gemini ({GEMINI_MODEL})...")

    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image {image_path}")
        return

    h, w = img.shape[:2]
    base64_image = image_to_base64(image_path)

    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=SYSTEM_PROMPT),
                        types.Part.from_text(
                            text="Analyze this construction drawing. Return the bounding boxes (0-1000 normalized) for all distinct plans, details, schedules, and metadata blocks."
                        ),
                        types.Part.from_bytes(
                            mime_type="image/png", data=base64.b64decode(base64_image)
                        ),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SegmentationProposal,
                thinkingConfig=types.ThinkingConfig(
                    thinkingLevel="low",
                ),
                media_resolution="MEDIA_RESOLUTION_MEDIUM",
            ),
        )

        # Parse JSON response
        try:
            proposal_dict = json.loads(response.text)
            proposal = SegmentationProposal(**proposal_dict)
        except json.JSONDecodeError:
            print(f"Error decoding JSON response: {response.text}")
            return
        except Exception as e:
            print(f"Error parsing response: {e}")
            return

        # Draw bounding boxes
        output_img = img.copy()

        # Colors for different types
        colors = {
            "plan": (0, 255, 0),  # Green
            "elevation": (0, 255, 0),  # Green
            "section": (0, 255, 0),  # Green
            "detail": (255, 0, 0),  # Blue
            "schedule": (0, 255, 255),  # Yellow
            "title_block": (0, 0, 255),  # Red
            "notes": (255, 0, 255),  # Magenta
            "legend": (255, 0, 255),  # Magenta
        }

        print(f"Found {len(proposal.regions)} regions:")

        for region in proposal.regions:
            color = colors.get(region.label, (128, 128, 128))  # Default Gray

            # Scale coordinates back to image dimensions
            x1 = int(region.xmin * w / 1000)
            y1 = int(region.ymin * h / 1000)
            x2 = int(region.xmax * w / 1000)
            y2 = int(region.ymax * h / 1000)

            # Draw rectangle
            cv2.rectangle(output_img, (x1, y1), (x2, y2), color, 5)

            # Draw label
            label_text = f"{region.label}: {region.description}"
            cv2.putText(
                output_img, label_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 3
            )

            print(f"- {region.label}: {region.description} ({x1}, {y1}, {x2}, {y2})")

        cv2.imwrite(output_path, output_img)
        print(f"Saved proposal to {output_path}")

    except Exception as e:
        print(f"Error calling Gemini API: {e}")


if __name__ == "__main__":
    # Example usage if run directly
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        out_path = img_path.replace(".png", "_gemini_proposal.png")
        propose_regions_gemini(img_path, out_path)
