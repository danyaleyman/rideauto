import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { MotionFadeUp } from "@/components/ui/motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Вход",
  description: "Вход в личный кабинет World Ride Auto",
};

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <MotionFadeUp>
        <Button variant="ghost" size="sm" className="mb-6 -ms-1 gap-1 ps-2 text-muted-foreground" asChild>
          <Link href="/">
            <ArrowLeft className="size-4" />
            На главную
          </Link>
        </Button>
      </MotionFadeUp>
      <MotionFadeUp delay={0.05}>
        <Card className="shadow-md ring-1 ring-border/60">
          <CardHeader>
            <CardTitle className="font-heading text-xl">Вход</CardTitle>
            <CardDescription>
              Раздел в разработке. Оформление заявки — через{" "}
              <Link href="/contacts" className="font-medium text-primary underline-offset-4 hover:underline">
                контакты
              </Link>
              .
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button className="w-full rounded-full" asChild>
              <Link href="/contacts">Связаться с менеджером</Link>
            </Button>
          </CardContent>
        </Card>
      </MotionFadeUp>
    </div>
  );
}
