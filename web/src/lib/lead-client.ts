import { readLeadErrorMessage } from "@/lib/lead-form-validation";

export type LeadRequestBody = {
  full_name: string;
  contact_method: string;
  message: string;
  pd_agree: boolean;
};

export async function submitLeadRequest(body: LeadRequestBody): Promise<{ ok: true } | { ok: false; message: string }> {
  const res = await fetch("/api/lead", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    return { ok: false, message: await readLeadErrorMessage(res) };
  }
  return { ok: true };
}
