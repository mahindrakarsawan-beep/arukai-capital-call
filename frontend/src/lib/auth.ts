/**
 * Auth utilities — server-side only.
 * Read/write the httpOnly JWT cookie.
 */

import { cookies } from "next/headers";

export const COOKIE_NAME = "arukai_token";

/** Read JWT from httpOnly cookie (server components / server actions). */
export async function getToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(COOKIE_NAME)?.value;
}

/** Write JWT into httpOnly cookie (called from server action after login). */
export async function setToken(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8, // 8 hours
  });
}

/** Clear JWT cookie (logout). */
export async function clearToken(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
}
