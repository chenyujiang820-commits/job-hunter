export type User = { id: string; username: string; role: string; status: string };
export type Evaluation = { id: string; job_id: string; score: number; decision: string; reasons: string[]; flags: string[]; notes: string };
export type Job = { id: string; source: string; external_job_id: string; title: string; company: string; location: string; salary: Record<string, unknown>; description: string; url: string; evaluation?: Evaluation | null };
export type SearchTemplate = { id: string; name: string; data: Record<string, unknown> };
export type Draft = { id: string; job_id: string; status: string; resume_text: string; cover_letter_text: string; fit: Record<string, unknown>; review: Record<string, unknown>; review_notes: string; output_file_ids: string[] };
export type MaterialBatch = { id: string; status: string; template_id: string; drafts: Draft[] };
