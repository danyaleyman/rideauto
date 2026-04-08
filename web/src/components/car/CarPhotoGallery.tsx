"use client";

import { useMemo, useState } from "react";
import Image from "next/image";

type CarPhotoGalleryProps = {
  images: string[];
  title: string;
};

export default function CarPhotoGallery({ images, title }: CarPhotoGalleryProps) {
  const valid = useMemo(() => images.filter((x) => /^https?:\/\//i.test(x)), [images]);
  const [active, setActive] = useState(0);

  if (!valid.length) return null;

  const current = valid[Math.min(active, valid.length - 1)] ?? valid[0];

  return (
    <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50">
        <Image
          src={current}
          alt={title}
          width={1280}
          height={760}
          sizes="(min-width: 1024px) 70vw, 96vw"
          className="h-[260px] w-full object-cover sm:h-[360px] lg:h-[460px]"
          priority
          decoding="async"
          unoptimized
        />
      </div>
      {valid.length > 1 ? (
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {valid.slice(0, 12).map((src, idx) => {
            const selected = idx === active;
            return (
              <button
                key={`${src}-${idx}`}
                type="button"
                onClick={() => setActive(idx)}
                className={`relative shrink-0 overflow-hidden rounded-lg border ${
                  selected ? "border-blue-500 ring-2 ring-blue-200" : "border-zinc-200"
                }`}
                aria-label={`Фото ${idx + 1}`}
              >
                <Image
                  src={src}
                  alt={`${title} превью ${idx + 1}`}
                  width={144}
                  height={92}
                  sizes="120px"
                  className="h-16 w-24 object-cover sm:h-[74px] sm:w-[116px]"
                  loading="lazy"
                  decoding="async"
                  unoptimized
                />
              </button>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
