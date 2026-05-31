"use client";

import { useMemo, useState } from "react";
import { Check, Copy, Download } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { isCarListingAdmin } from "@/lib/car-admin-access";
import { downloadCarPhotos } from "@/lib/car-admin-download-photos";
import { useLocaleContext } from "@/components/LocaleProvider";
import { buildCarSocialDescription } from "@/lib/car-social-description";

type Props = {
  carId: string;
  title: string;
  data: Record<string, unknown>;
  photoUrls: string[];
  priceRub: number | null;
  priceOnRequest?: boolean;
  publishedAt?: string | null;
};

export function CarAdminPanel({
  carId,
  title,
  data,
  photoUrls,
  priceRub,
  priceOnRequest,
  publishedAt,
}: Props) {
  const { t } = useLocaleContext();
  const { loading, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const isAdmin = !loading && isCarListingAdmin(user?.email);

  const socialText = useMemo(
    () =>
      buildCarSocialDescription({
        carId,
        title,
        data,
        priceRub,
        priceOnRequest,
        publishedAt,
      }),
    [carId, title, data, priceRub, priceOnRequest, publishedAt],
  );

  if (!isAdmin) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full font-medium">
          {t("admin.carPanelTitle")}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle>{t("admin.carPanelTitle")}</DialogTitle>
          <DialogDescription>{t("admin.carPanelDesc", { carId })}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-2.5">
          <Button
            type="button"
            variant="secondary"
            className="w-full justify-start gap-2"
            disabled={downloading || !photoUrls.length}
            onClick={() => {
              setActionError(null);
              setDownloading(true);
              setDownloadProgress(null);
              void downloadCarPhotos(photoUrls, carId, (done, total) => {
                setDownloadProgress(`${done} / ${total}`);
              })
                .catch((err: unknown) => {
                  const msg = err instanceof Error ? err.message : t("admin.downloadFailed");
                  setActionError(msg);
                })
                .finally(() => {
                  setDownloading(false);
                  setDownloadProgress(null);
                });
            }}
          >
            <Download className="size-4 shrink-0" aria-hidden />
            {downloading
              ? downloadProgress
                ? t("admin.downloadingProgress", { progress: downloadProgress })
                : t("admin.downloading")
              : t("admin.downloadPhotos")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            className="w-full justify-start gap-2"
            onClick={() => {
              setActionError(null);
              void navigator.clipboard.writeText(socialText).then(() => {
                setCopied(true);
                window.setTimeout(() => setCopied(false), 2000);
              });
            }}
          >
            {copied ? (
              <Check className="size-4 shrink-0 text-green-600" aria-hidden />
            ) : (
              <Copy className="size-4 shrink-0" aria-hidden />
            )}
            {copied ? t("admin.descriptionCopied") : t("admin.copyDescription")}
          </Button>
          {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
          {!photoUrls.length ? (
            <p className="text-xs text-muted-foreground">{t("admin.noPhotos")}</p>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
