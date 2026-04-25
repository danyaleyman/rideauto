"use client";

import { motion, type MotionProps } from "framer-motion";
import type { ReactNode } from "react";

const SOFT_EASE = [0.22, 1, 0.36, 1] as const;
const defaultTransition = { duration: 0.38, ease: SOFT_EASE };

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

export function MotionStagger({
  children,
  className,
  delayChildren = 0.03,
  staggerChildren = 0.04,
}: {
  children: ReactNode;
  className?: string;
  delayChildren?: number;
  staggerChildren?: number;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-80px" }}
      variants={{
        hidden: {},
        show: {
          transition: { delayChildren, staggerChildren },
        },
      }}
    >
      {children}
    </motion.div>
  );
}

export function MotionStaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 10, scale: 0.995 },
        show: {
          opacity: 1,
          y: 0,
          scale: 1,
          transition: { duration: 0.28, ease: SOFT_EASE },
        },
      }}
    >
      {children}
    </motion.div>
  );
}
