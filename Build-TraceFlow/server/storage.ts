import { db } from "./db";
import {
  type User,
  type UpsertUser,
  type Project,
  type InsertProject,
  type Drawing,
  type InsertDrawing,
  type Sheet,
  type InsertSheet,
  type Overlay,
  type InsertOverlay,
  type Change,
  type InsertChange,
  type CostAnalysis,
  type InsertCostAnalysis,
  users,
  projects,
  drawings,
  sheets,
  overlays,
  changes,
  costAnalyses,
} from "@shared/schema";
import { eq, and, desc } from "drizzle-orm";

export interface IStorage {
  // Users (managed by Replit Auth - mainly for reference)
  getUser(id: string): Promise<User | undefined>;
  getUserByEmail(email: string): Promise<User | undefined>;
  createUser(user: UpsertUser): Promise<User>;

  // Projects
  createProject(project: InsertProject): Promise<Project>;
  getProject(id: string): Promise<Project | undefined>;
  getProjectsByOrganization(organizationId: string): Promise<Project[]>;
  updateProject(id: string, data: Partial<InsertProject>): Promise<Project | undefined>;

  // Drawings
  createDrawing(drawing: InsertDrawing): Promise<Drawing>;
  getDrawing(id: string): Promise<Drawing | undefined>;
  getDrawingsByProject(projectId: string): Promise<Drawing[]>;
  updateDrawing(id: string, data: Partial<InsertDrawing>): Promise<Drawing | undefined>;

  // Sheets
  createSheet(sheet: InsertSheet): Promise<Sheet>;
  getSheetsByDrawing(drawingId: string): Promise<Sheet[]>;
  getSheet(id: string): Promise<Sheet | undefined>;

  // Overlays (Comparisons)
  createOverlay(overlay: InsertOverlay): Promise<Overlay>;
  getOverlay(id: string): Promise<Overlay | undefined>;
  getOverlaysByBlock(blockId: string): Promise<Overlay[]>;
  updateOverlay(id: string, data: Partial<InsertOverlay>): Promise<Overlay | undefined>;

  // Changes
  createChange(change: InsertChange): Promise<Change>;
  getChangesByOverlay(overlayId: string): Promise<Change[]>;
  getChange(id: string): Promise<Change | undefined>;
  updateChange(id: string, data: Partial<InsertChange>): Promise<Change | undefined>;
  deleteChange(id: string): Promise<void>;

  // Cost Analyses
  createCostAnalysis(analysis: InsertCostAnalysis): Promise<CostAnalysis>;
  getCostAnalysisByOverlay(overlayId: string): Promise<CostAnalysis | undefined>;
  updateCostAnalysis(id: string, data: Partial<InsertCostAnalysis>): Promise<CostAnalysis | undefined>;
}

export class DatabaseStorage implements IStorage {
  // Users
  async getUser(id: string): Promise<User | undefined> {
    const result = await db.select().from(users).where(eq(users.id, id));
    return result[0];
  }

  async getUserByEmail(email: string): Promise<User | undefined> {
    const result = await db.select().from(users).where(eq(users.email, email));
    return result[0];
  }

  async createUser(user: UpsertUser): Promise<User> {
    const result = await db.insert(users).values(user).returning();
    return result[0];
  }

  // Projects
  async createProject(project: InsertProject): Promise<Project> {
    const result = await db.insert(projects).values(project).returning();
    return result[0];
  }

  async getProject(id: string): Promise<Project | undefined> {
    const result = await db.select().from(projects).where(eq(projects.id, id));
    return result[0];
  }

  async getProjectsByOrganization(organizationId: string): Promise<Project[]> {
    return await db.select().from(projects)
      .where(eq(projects.organizationId, organizationId))
      .orderBy(desc(projects.createdAt));
  }

  async updateProject(id: string, data: Partial<InsertProject>): Promise<Project | undefined> {
    const result = await db.update(projects)
      .set(data)
      .where(eq(projects.id, id))
      .returning();
    return result[0];
  }

  // Drawings
  async createDrawing(drawing: InsertDrawing): Promise<Drawing> {
    const result = await db.insert(drawings).values(drawing).returning();
    return result[0];
  }

  async getDrawing(id: string): Promise<Drawing | undefined> {
    const result = await db.select().from(drawings).where(eq(drawings.id, id));
    return result[0];
  }

  async getDrawingsByProject(projectId: string): Promise<Drawing[]> {
    return await db.select().from(drawings)
      .where(eq(drawings.projectId, projectId))
      .orderBy(desc(drawings.createdAt));
  }

  async updateDrawing(id: string, data: Partial<InsertDrawing>): Promise<Drawing | undefined> {
    const result = await db.update(drawings)
      .set(data)
      .where(eq(drawings.id, id))
      .returning();
    return result[0];
  }

  // Sheets
  async createSheet(sheet: InsertSheet): Promise<Sheet> {
    const result = await db.insert(sheets).values(sheet).returning();
    return result[0];
  }

  async getSheetsByDrawing(drawingId: string): Promise<Sheet[]> {
    return await db.select().from(sheets)
      .where(eq(sheets.drawingId, drawingId));
  }

  async getSheet(id: string): Promise<Sheet | undefined> {
    const result = await db.select().from(sheets).where(eq(sheets.id, id));
    return result[0];
  }

  // Overlays (Comparisons)
  async createOverlay(overlay: InsertOverlay): Promise<Overlay> {
    const result = await db.insert(overlays).values(overlay).returning();
    return result[0];
  }

  async getOverlay(id: string): Promise<Overlay | undefined> {
    const result = await db.select().from(overlays).where(eq(overlays.id, id));
    return result[0];
  }

  async getOverlaysByBlock(blockId: string): Promise<Overlay[]> {
    return await db.select().from(overlays)
      .where(eq(overlays.blockAId, blockId))
      .orderBy(desc(overlays.createdAt));
  }

  async updateOverlay(id: string, data: Partial<InsertOverlay>): Promise<Overlay | undefined> {
    const result = await db.update(overlays)
      .set(data)
      .where(eq(overlays.id, id))
      .returning();
    return result[0];
  }

  // Changes
  async createChange(change: InsertChange): Promise<Change> {
    const result = await db.insert(changes).values(change).returning();
    return result[0];
  }

  async getChangesByOverlay(overlayId: string): Promise<Change[]> {
    return await db.select().from(changes)
      .where(eq(changes.overlayId, overlayId))
      .orderBy(desc(changes.createdAt));
  }

  async getChange(id: string): Promise<Change | undefined> {
    const result = await db.select().from(changes).where(eq(changes.id, id));
    return result[0];
  }

  async updateChange(id: string, data: Partial<InsertChange>): Promise<Change | undefined> {
    const result = await db.update(changes)
      .set(data)
      .where(eq(changes.id, id))
      .returning();
    return result[0];
  }

  async deleteChange(id: string): Promise<void> {
    await db.delete(changes).where(eq(changes.id, id));
  }

  // Cost Analyses
  async createCostAnalysis(analysis: InsertCostAnalysis): Promise<CostAnalysis> {
    const result = await db.insert(costAnalyses).values(analysis).returning();
    return result[0];
  }

  async getCostAnalysisByOverlay(overlayId: string): Promise<CostAnalysis | undefined> {
    const result = await db.select().from(costAnalyses)
      .where(eq(costAnalyses.overlayId, overlayId));
    return result[0];
  }

  async updateCostAnalysis(id: string, data: Partial<InsertCostAnalysis>): Promise<CostAnalysis | undefined> {
    const result = await db.update(costAnalyses)
      .set(data)
      .where(eq(costAnalyses.id, id))
      .returning();
    return result[0];
  }
}

export const storage = new DatabaseStorage();
