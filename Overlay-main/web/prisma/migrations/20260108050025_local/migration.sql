-- CreateEnum
CREATE TYPE "BlockType" AS ENUM ('Plan', 'Elevation', 'Section', 'Detail', 'Keynote', 'Legend', 'Diagram', 'KeyPlan', 'North Arrow', 'General Note', 'Schedule', 'Revision History', 'Project Info', 'General Notes', 'Key Notes', 'Sheet Notes', 'Abbreviations', 'Code References', 'Notes', 'Title Block', 'Consultants', 'Seals', 'Change', 'Clash');

-- CreateEnum
CREATE TYPE "JobStatus" AS ENUM ('Queued', 'Started', 'Completed', 'Failed', 'Canceled');

-- CreateTable
CREATE TABLE "projects" (
    "id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "deleted_at" TIMESTAMP(3),
    "organization_id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,

    CONSTRAINT "projects_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "drawings" (
    "id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "deleted_at" TIMESTAMP(3),
    "project_id" TEXT NOT NULL,
    "filename" TEXT NOT NULL,
    "name" TEXT,
    "uri" TEXT NOT NULL,

    CONSTRAINT "drawings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sheets" (
    "id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "deleted_at" TIMESTAMP(3),
    "drawing_id" TEXT NOT NULL,
    "index" INTEGER NOT NULL,
    "uri" TEXT NOT NULL,
    "title" TEXT,
    "sheet_number" TEXT,
    "discipline" TEXT,
    "metadata" JSONB,

    CONSTRAINT "sheets_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "blocks" (
    "id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "deleted_at" TIMESTAMP(3),
    "sheet_id" TEXT NOT NULL,
    "type" "BlockType",
    "uri" TEXT,
    "bounds" JSONB,
    "ocr" TEXT,
    "description" TEXT,
    "metadata" JSONB,

    CONSTRAINT "blocks_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "overlays" (
    "id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "deleted_at" TIMESTAMP(3),
    "block_a_id" TEXT NOT NULL,
    "block_b_id" TEXT NOT NULL,
    "job_id" TEXT,
    "uri" TEXT,
    "addition_uri" TEXT,
    "deletion_uri" TEXT,
    "score" DOUBLE PRECISION,
    "summary" JSONB,
    "changes" JSONB[],
    "clashes" JSONB[],

    CONSTRAINT "overlays_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "jobs" (
    "id" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "project_id" TEXT,
    "parent_id" TEXT,
    "target_type" TEXT NOT NULL,
    "target_id" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "status" "JobStatus" NOT NULL,
    "payload" JSONB NOT NULL,
    "events" JSONB,

    CONSTRAINT "jobs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "projects_organization_id_idx" ON "projects"("organization_id");

-- CreateIndex
CREATE INDEX "drawings_project_id_idx" ON "drawings"("project_id");

-- CreateIndex
CREATE UNIQUE INDEX "sheets_drawing_id_index_key" ON "sheets"("drawing_id", "index");

-- CreateIndex
CREATE INDEX "blocks_sheet_id_idx" ON "blocks"("sheet_id");

-- CreateIndex
CREATE INDEX "blocks_type_idx" ON "blocks"("type");

-- CreateIndex
CREATE INDEX "overlays_block_a_id_idx" ON "overlays"("block_a_id");

-- CreateIndex
CREATE INDEX "overlays_block_b_id_idx" ON "overlays"("block_b_id");

-- CreateIndex
CREATE INDEX "overlays_job_id_idx" ON "overlays"("job_id");

-- CreateIndex
CREATE INDEX "jobs_project_id_created_at_idx" ON "jobs"("project_id", "created_at");

-- CreateIndex
CREATE INDEX "jobs_type_idx" ON "jobs"("type");

-- CreateIndex
CREATE INDEX "jobs_status_idx" ON "jobs"("status");

-- CreateIndex
CREATE INDEX "jobs_target_type_target_id_idx" ON "jobs"("target_type", "target_id");

-- CreateIndex
CREATE INDEX "jobs_parent_id_idx" ON "jobs"("parent_id");

-- AddForeignKey
ALTER TABLE "drawings" ADD CONSTRAINT "drawings_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sheets" ADD CONSTRAINT "sheets_drawing_id_fkey" FOREIGN KEY ("drawing_id") REFERENCES "drawings"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "blocks" ADD CONSTRAINT "blocks_sheet_id_fkey" FOREIGN KEY ("sheet_id") REFERENCES "sheets"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "overlays" ADD CONSTRAINT "overlays_block_a_id_fkey" FOREIGN KEY ("block_a_id") REFERENCES "blocks"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "overlays" ADD CONSTRAINT "overlays_block_b_id_fkey" FOREIGN KEY ("block_b_id") REFERENCES "blocks"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "overlays" ADD CONSTRAINT "overlays_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "jobs"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "jobs" ADD CONSTRAINT "jobs_parent_id_fkey" FOREIGN KEY ("parent_id") REFERENCES "jobs"("id") ON DELETE SET NULL ON UPDATE CASCADE;
