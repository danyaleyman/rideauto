"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

export const MOTION_TOKENS = {
  easeSoft: [0.22, 1, 0.36, 1] as const,
  duration: {
    fast: 0.18,
    base: 0.26,
    reveal: 0.38,
  },
  offsets: {
    fadeUp: 18,
    fadeUpSm: 10,
  },
  stagger: {
    delayChildren: 0.03,
    staggerChildren: 0.04,
  },
} as const;

export const MOTION_PRESETS = {
  fadeUpInitial: { opacity: 0, y: MOTION_TOKENS.offsets.fadeUp },
  fadeUpAnimate: { opacity: 1, y: 0 },
  revealTransition: { duration: MOTION_TOKENS.duration.reveal, ease: MOTION_TOKENS.easeSoft },
  popInInitial: { opacity: 0, scale: 0.94 },
  popInAnimate: { opacity: 1, scale: 1 },
  popInExit: { opacity: 0, scale: 0.94 },
  pressable: { whileTap: { scale: 0.99 }, transition: { duration: 0.12 } },
  hoverLiftSm: { whileHover: { y: -1 }, transition: { duration: MOTION_TOKENS.duration.fast } },
} as const;

export function MotionFadeUp({
  children,
  className,
  delay = 0,
  ...props
}: React.ComponentProps<typeof motion.div> & {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduceMotion ? false : MOTION_PRESETS.fadeUpInitial}
      whileInView={MOTION_PRESETS.fadeUpAnimate}
      viewport={{ once: true, margin: "-80px" }}
      transition={
        reduceMotion
          ? { duration: 0.01 }
          : { ...MOTION_PRESETS.revealTransition, delay }
      }
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function MotionStagger({
  children,
  className,
  delayChildren = MOTION_TOKENS.stagger.delayChildren,
  staggerChildren = MOTION_TOKENS.stagger.staggerChildren,
  ...props
}: {
  children: ReactNode;
  className?: string;
  delayChildren?: number;
  staggerChildren?: number;
} & React.ComponentProps<typeof motion.div>) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduceMotion ? false : "hidden"}
      whileInView={reduceMotion ? undefined : "show"}
      viewport={{ once: true, margin: "-80px" }}
      variants={
        reduceMotion
          ? undefined
          : {
              hidden: {},
              show: {
                transition: { delayChildren, staggerChildren },
              },
            }
      }
      {...props}
    >
      {children}
    </motion.div>
  );
}

export function MotionStaggerItem({
  children,
  className,
  ...props
}: {
  children: ReactNode;
  className?: string;
} & React.ComponentProps<typeof motion.div>) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.div
      className={className}
      variants={
        reduceMotion
          ? undefined
          : {
              hidden: { opacity: 0, y: MOTION_TOKENS.offsets.fadeUpSm, scale: 0.995 },
              show: {
                opacity: 1,
                y: 0,
                scale: 1,
                transition: { duration: MOTION_TOKENS.duration.base, ease: MOTION_TOKENS.easeSoft },
              },
            }
      }
      {...props}
    >
      {children}
    </motion.div>
  );
}
