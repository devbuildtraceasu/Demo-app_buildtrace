import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { setupAuth, registerAuthRoutes, isAuthenticated } from "./replit_integrations/auth";
import { insertProjectSchema, insertDrawingSchema, insertOverlaySchema, insertChangeSchema, insertCostAnalysisSchema } from "@shared/schema";

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {
  // Setup authentication (MUST be before other routes)
  await setupAuth(app);
  registerAuthRoutes(app);

  // Projects API
  app.post("/api/projects", isAuthenticated, async (req: any, res) => {
    try {
      const organizationId = req.user?.claims?.organization_id || "default-org";
      const projectData = insertProjectSchema.parse({ ...req.body, organizationId });
      const project = await storage.createProject(projectData);
      res.json(project);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/projects", isAuthenticated, async (req: any, res) => {
    try {
      const organizationId = req.user?.claims?.organization_id || "default-org";
      const projects = await storage.getProjectsByOrganization(organizationId);
      res.json(projects);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.get("/api/projects/:id", isAuthenticated, async (req, res) => {
    try {
      const project = await storage.getProject(req.params.id);
      if (!project) {
        return res.status(404).json({ message: "Project not found" });
      }
      res.json(project);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.patch("/api/projects/:id", isAuthenticated, async (req, res) => {
    try {
      const project = await storage.updateProject(req.params.id, req.body);
      if (!project) {
        return res.status(404).json({ message: "Project not found" });
      }
      res.json(project);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  // Drawings API
  app.post("/api/projects/:projectId/drawings", isAuthenticated, async (req, res) => {
    try {
      const drawingData = insertDrawingSchema.parse({
        ...req.body,
        projectId: req.params.projectId,
      });
      const drawing = await storage.createDrawing(drawingData);
      res.json(drawing);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/projects/:projectId/drawings", isAuthenticated, async (req, res) => {
    try {
      const drawings = await storage.getDrawingsByProject(req.params.projectId);
      res.json(drawings);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.get("/api/drawings/:id", isAuthenticated, async (req, res) => {
    try {
      const drawing = await storage.getDrawing(req.params.id);
      if (!drawing) {
        return res.status(404).json({ message: "Drawing not found" });
      }
      res.json(drawing);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.get("/api/drawings/:id/sheets", isAuthenticated, async (req, res) => {
    try {
      const sheets = await storage.getSheetsByDrawing(req.params.id);
      res.json(sheets);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  // Overlays API (Comparisons)
  app.post("/api/overlays", isAuthenticated, async (req, res) => {
    try {
      const overlayData = insertOverlaySchema.parse(req.body);
      const overlay = await storage.createOverlay(overlayData);
      res.json(overlay);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/overlays/:id", isAuthenticated, async (req, res) => {
    try {
      const overlay = await storage.getOverlay(req.params.id);
      if (!overlay) {
        return res.status(404).json({ message: "Overlay not found" });
      }
      res.json(overlay);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.patch("/api/overlays/:id", isAuthenticated, async (req, res) => {
    try {
      const overlay = await storage.updateOverlay(req.params.id, req.body);
      if (!overlay) {
        return res.status(404).json({ message: "Overlay not found" });
      }
      res.json(overlay);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  // Changes API
  app.post("/api/overlays/:overlayId/changes", isAuthenticated, async (req, res) => {
    try {
      const changeData = insertChangeSchema.parse({
        ...req.body,
        overlayId: req.params.overlayId,
      });
      const change = await storage.createChange(changeData);
      res.json(change);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/overlays/:overlayId/changes", isAuthenticated, async (req, res) => {
    try {
      const changes = await storage.getChangesByOverlay(req.params.overlayId);
      res.json(changes);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.patch("/api/changes/:id", isAuthenticated, async (req, res) => {
    try {
      const change = await storage.updateChange(req.params.id, req.body);
      if (!change) {
        return res.status(404).json({ message: "Change not found" });
      }
      res.json(change);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.delete("/api/changes/:id", isAuthenticated, async (req, res) => {
    try {
      await storage.deleteChange(req.params.id);
      res.json({ message: "Change deleted" });
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  // Cost Analysis API
  app.post("/api/overlays/:overlayId/cost-analysis", isAuthenticated, async (req, res) => {
    try {
      const analysisData = insertCostAnalysisSchema.parse({
        ...req.body,
        overlayId: req.params.overlayId,
      });
      const analysis = await storage.createCostAnalysis(analysisData);
      res.json(analysis);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/overlays/:overlayId/cost-analysis", isAuthenticated, async (req, res) => {
    try {
      const analysis = await storage.getCostAnalysisByOverlay(req.params.overlayId);
      if (!analysis) {
        return res.status(404).json({ message: "Cost analysis not found" });
      }
      res.json(analysis);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  return httpServer;
}
