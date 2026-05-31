/** Достраивает поля Che168 из che168_params_raw (без перескрапа БД). */



import {

  isSpecPlaceholder,

  resolveChe168DisplacementLiters,

  resolveChe168Drive,

  resolveChe168Gearbox,

  resolveChe168PowerHp,

  resolveChe168TorqueNm,

} from "@/lib/che168-spec-resolve";



export function enrichChe168CarSpecs(data: Record<string, unknown>): Record<string, unknown> {

  const src = String(data.source ?? "").trim().toLowerCase();

  if (src !== "che168" && src !== "china") return data;

  const raw = data.che168_params_raw;

  if (!raw || typeof raw !== "object") return data;



  const engineText = typeof data.engine === "string" ? data.engine.trim() : "";

  const patch: Record<string, unknown> = {};



  const gearbox = resolveChe168Gearbox(raw, data.transmission_type);

  if (gearbox) {
    patch.transmission_type = gearbox;
    patch.transmission_type_ru = gearbox;
  }



  const drive = resolveChe168Drive(raw, data.drive_type);

  if (drive) patch.drive_type = drive;



  const powerHp = resolveChe168PowerHp(raw, engineText);

  if (powerHp != null) patch.power_hp = powerHp;



  const torque = resolveChe168TorqueNm(raw);

  if (torque != null) patch.torque_nm = torque;



  const dispL = resolveChe168DisplacementLiters(raw);

  if (dispL) patch.displacement_liters_label = dispL;



  const out: Record<string, unknown> = { ...data, ...patch };

  if (isSpecPlaceholder(out.drive_type)) delete out.drive_type;

  return out;

}

