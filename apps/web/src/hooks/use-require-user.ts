"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchMe, type AuthUser } from "@/lib/api";

export function useRequireUser(nextPath: string) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let settled = false;
    const goLogin = () => {
      router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
    };
    const timer = window.setTimeout(() => {
      // Avoid infinite "Checking session…" if the API/tunnel hangs.
      if (!cancelled && !settled) {
        settled = true;
        setLoading(false);
        goLogin();
      }
    }, 12000);
    fetchMe()
      .then((me) => {
        if (!cancelled && !settled) {
          settled = true;
          setUser(me);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled && !settled) {
          settled = true;
          setLoading(false);
          goLogin();
        }
      })
      .finally(() => {
        window.clearTimeout(timer);
      });
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [router, nextPath]);

  return { user, loading };
}
