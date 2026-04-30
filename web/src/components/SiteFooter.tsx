"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { COOKIE_CONSENT_OPEN_EVENT } from "@/lib/cookie-consent";

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-muted/25 py-8 text-sm text-muted-foreground">
      <div className="mx-auto flex min-w-0 max-w-[1440px] flex-col gap-4 px-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:px-6 lg:px-10">
        <nav className="flex flex-wrap gap-x-4 gap-y-1">
          <motion.div whileHover={{ y: -1 }} transition={{ duration: 0.16 }}>
            <Link className="transition-colors hover:text-foreground" href="/privacy">
              Конфиденциальность
            </Link>
          </motion.div>
          <motion.div whileHover={{ y: -1 }} transition={{ duration: 0.16 }}>
            <Link className="transition-colors hover:text-foreground" href="/cookies">
              Cookie
            </Link>
          </motion.div>
          <motion.div whileHover={{ y: -1 }} transition={{ duration: 0.16 }}>
            <Link className="transition-colors hover:text-foreground" href="/agreement">
              Соглашение
            </Link>
          </motion.div>
          <motion.div whileHover={{ y: -1 }} transition={{ duration: 0.16 }}>
            <button
              type="button"
              className="transition-colors hover:text-foreground"
              onClick={() => window.dispatchEvent(new CustomEvent(COOKIE_CONSENT_OPEN_EVENT))}
            >
              Управление cookie
            </button>
          </motion.div>
        </nav>
        <motion.p
          className="shrink-0 text-muted-foreground"
          initial={{ opacity: 0, y: 6 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.25 }}
        >
          © World Ride Auto 2026
        </motion.p>
      </div>
    </footer>
  );
}
