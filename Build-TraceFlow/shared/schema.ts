import { sql } from "drizzle-orm";
import { pgTable, text, varchar, timestamp, integer, boolean, jsonb, index, doublePrecision } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// Session storage table
export const sessions = pgTable(
  "sessions",
  {
    sid: varchar("sid").primaryKey(),
    sess: jsonb("sess").notNull(),
    expire: timestamp("expire").notNull(),
  },
  (table) => [index("IDX_session_expire").on(table.expire)]
);

// Organizations table
export const organizations = pgTable("organizations", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  name: text("name").notNull(),
  slug: text("slug").unique().notNull(),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export type Organization = typeof organizations.$inferSelect;

// Users table
export const users = pgTable("users", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  email: varchar("email").unique().notNull(),
  passwordHash: varchar("password_hash"),
  firstName: varchar("first_name"),
  lastName: varchar("last_name"),
  profileImageUrl: varchar("profile_image_url"),
  googleId: varchar("google_id").unique(),
  organizationId: varchar("organization_id").references(() => organizations.id),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export type UpsertUser = typeof users.$inferInsert;
export type User = typeof users.$inferSelect;

// Projects table
export const projects = pgTable("projects", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  organizationId: varchar("organization_id").notNull().references(() => organizations.id),
  name: text("name").notNull(),
  description: text("description"),
  projectNumber: text("project_number"),
  address: text("address"),
  projectType: text("project_type"),
  phase: text("phase"),
  owner: text("owner"),
  contractor: text("contractor"),
  architect: text("architect"),
  projectManager: text("project_manager"),
  contractValue: text("contract_value"),
  targetCompletion: text("target_completion"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export const insertProjectSchema = createInsertSchema(projects).omit({ id: true, createdAt: true, updatedAt: true, deletedAt: true });
export type InsertProject = z.infer<typeof insertProjectSchema>;
export type Project = typeof projects.$inferSelect;

// Drawings table (replaces drawing_sets)
export const drawings = pgTable("drawings", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  projectId: varchar("project_id").notNull().references(() => projects.id),
  filename: text("filename").notNull(),
  name: text("name"),
  uri: text("uri").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export const insertDrawingSchema = createInsertSchema(drawings).omit({ id: true, createdAt: true, updatedAt: true, deletedAt: true });
export type InsertDrawing = z.infer<typeof insertDrawingSchema>;
export type Drawing = typeof drawings.$inferSelect;

// Sheets table
export const sheets = pgTable("sheets", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  drawingId: varchar("drawing_id").notNull().references(() => drawings.id),
  index: integer("index").notNull(),
  uri: text("uri").notNull(),
  title: text("title"),
  sheetNumber: text("sheet_number"),
  discipline: text("discipline"),
  metadata: jsonb("metadata"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export const insertSheetSchema = createInsertSchema(sheets).omit({ id: true, createdAt: true, updatedAt: true, deletedAt: true });
export type InsertSheet = z.infer<typeof insertSheetSchema>;
export type Sheet = typeof sheets.$inferSelect;

// Blocks table
export const blocks = pgTable("blocks", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  sheetId: varchar("sheet_id").notNull().references(() => sheets.id),
  type: text("type"),
  uri: text("uri"),
  bounds: jsonb("bounds"),
  ocr: text("ocr"),
  description: text("description"),
  metadata: jsonb("metadata"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export const insertBlockSchema = createInsertSchema(blocks).omit({ id: true, createdAt: true, updatedAt: true, deletedAt: true });
export type InsertBlock = z.infer<typeof insertBlockSchema>;
export type Block = typeof blocks.$inferSelect;

// Overlays table (comparison results)
export const overlays = pgTable("overlays", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  blockAId: varchar("block_a_id").notNull().references(() => blocks.id),
  blockBId: varchar("block_b_id").notNull().references(() => blocks.id),
  jobId: varchar("job_id"),
  uri: text("uri"),
  additionUri: text("addition_uri"),
  deletionUri: text("deletion_uri"),
  score: doublePrecision("score"),
  summary: jsonb("summary"),
  changesJson: jsonb("changes").default(sql`'[]'::jsonb`),
  clashes: jsonb("clashes").default(sql`'[]'::jsonb`),
  alignmentMethod: text("alignment_method"),
  alignmentStats: jsonb("alignment_stats"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export const insertOverlaySchema = createInsertSchema(overlays).omit({ id: true, createdAt: true, updatedAt: true, deletedAt: true });
export type InsertOverlay = z.infer<typeof insertOverlaySchema>;
export type Overlay = typeof overlays.$inferSelect;

// Jobs table
export const jobs = pgTable("jobs", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  projectId: varchar("project_id").references(() => projects.id),
  parentId: varchar("parent_id"),
  targetType: text("target_type").notNull(),
  targetId: text("target_id").notNull(),
  type: text("type").notNull(),
  status: text("status").notNull().default("Queued"),
  payload: jsonb("payload").default(sql`'{}'::jsonb`),
  events: jsonb("events"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const insertJobSchema = createInsertSchema(jobs).omit({ id: true, createdAt: true, updatedAt: true });
export type InsertJob = z.infer<typeof insertJobSchema>;
export type Job = typeof jobs.$inferSelect;

// Changes table
export const changes = pgTable("changes", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  overlayId: varchar("overlay_id").notNull().references(() => overlays.id),
  type: text("type").notNull(), // "added", "removed", "modified"
  title: text("title").notNull(),
  description: text("description"),
  bounds: jsonb("bounds"),
  coordinates: text("coordinates"),
  sheetNumber: text("sheet_number"),
  trade: text("trade"),
  discipline: text("discipline"),
  estimatedCost: text("estimated_cost"),
  scheduleImpact: text("schedule_impact"),
  status: text("status").default("open"),
  assigneeId: varchar("assignee_id").references(() => users.id),
  aiConfidence: doublePrecision("ai_confidence"),
  aiMetadata: jsonb("ai_metadata"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
  deletedAt: timestamp("deleted_at"),
});

export const insertChangeSchema = createInsertSchema(changes).omit({ id: true, createdAt: true, updatedAt: true, deletedAt: true });
export type InsertChange = z.infer<typeof insertChangeSchema>;
export type Change = typeof changes.$inferSelect;

// Comments table
export const comments = pgTable("comments", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  changeId: varchar("change_id").notNull().references(() => changes.id),
  authorName: text("author_name").notNull(),
  authorEmail: text("author_email").notNull(),
  content: text("content").notNull(),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const insertCommentSchema = createInsertSchema(comments).omit({ id: true, createdAt: true, updatedAt: true });
export type InsertComment = z.infer<typeof insertCommentSchema>;
export type Comment = typeof comments.$inferSelect;

// Cost Analysis table
export const costAnalyses = pgTable("cost_analyses", {
  id: varchar("id").primaryKey().default(sql`gen_random_uuid()`),
  overlayId: varchar("overlay_id").notNull().unique().references(() => overlays.id),
  projectId: varchar("project_id").notNull().references(() => projects.id),
  totalCostImpact: text("total_cost_impact"),
  totalScheduleImpact: text("total_schedule_impact"),
  biggestCostDriver: text("biggest_cost_driver"),
  tradeBreakdown: jsonb("trade_breakdown"),
  analysisData: jsonb("analysis_data"),
  status: text("status").default("pending"),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow(),
});

export const insertCostAnalysisSchema = createInsertSchema(costAnalyses).omit({ id: true, createdAt: true, updatedAt: true });
export type InsertCostAnalysis = z.infer<typeof insertCostAnalysisSchema>;
export type CostAnalysis = typeof costAnalyses.$inferSelect;
