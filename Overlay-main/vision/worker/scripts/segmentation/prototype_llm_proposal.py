import base64
import os
import sys

import cv2
import openai
from pydantic import BaseModel, Field

# Add worker root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from dotenv import load_dotenv

# Load .env from worker root
worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
load_dotenv(os.path.join(worker_root, ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

if not OPENAI_API_KEY:
    # Try getting it from config as fallback (might fail if other env vars missing)
    try:
        from config import config

        OPENAI_API_KEY = config.openai_api_key
        OPENAI_MODEL = config.openai_model
    except Exception as e:
        print(f"Warning: Could not load config: {e}")

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY not found in environment or config.")
    sys.exit(1)


class BoundingBox(BaseModel):
    label: str = Field(
        description="Type of region: 'plan', 'elevation', 'section', 'detail', 'schedule', 'title_block', 'notes', 'legend'"
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
- General Notes or Legends

For each block, estimate a bounding box that encompasses the entire content of that block.
IMPORTANT: Return coordinates normalized to a 1000x1000 grid (0-1000).
ymin, xmin, ymax, xmax."""


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def propose_regions_llm(image_path: str, output_path: str):
    print(f"Processing {image_path} with LLM ({OPENAI_MODEL})...")

    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image {image_path}")
        return

    h, w = img.shape[:2]
    base64_image = image_to_base64(image_path)

    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    try:
        response = client.beta.chat.completions.parse(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this construction drawing. Return the bounding boxes (0-1000 normalized) for all distinct plans, details, schedules, and metadata blocks.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            response_format=SegmentationProposal,
        )

        proposal = response.choices[0].message.parsed

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
        print(f"Error calling OpenAI API: {e}")


if __name__ == "__main__":
    # Example usage if run directly
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        out_path = img_path.replace(".png", "_llm_proposal.png")
        propose_regions_llm(img_path, out_path)
