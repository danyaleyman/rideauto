"use client";

import { motion, type MotionProps } from "framer-motion";
import type { ReactNode } from "react";

const defaultTransition = { duration: 0.38, ease: [0.22, 1, 0.36, 1] as const };

export function MotionFadeUp({
  children,
  className,
  delay = 0,
  ...props
}: MotionProps & {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ ...defaultTransition, delay }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
