"use server";

/**
 * Server actions for login / logout.
 * These run server-side so they can set httpOnly cookies.
 */

import { redirect } from "next/navigation";
import { login } from "./api";
import { clearToken, setToken } from "./auth";

export async function loginAction(
  _prevState: { error: string | null },
  formData: FormData
): Promise<{ error: string | null }> {
  const email = (formData.get("email") as string | null) ?? "";
  const password = (formData.get("password") as string | null) ?? "";

  if (!email || !password) {
    return { error: "Email and password are required." };
  }

  try {
    const { access_token } = await login(email, password);
    await setToken(access_token);
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Login failed. Please try again.";
    return { error: message };
  }

  redirect("/documents");
}

export async function logoutAction(): Promise<void> {
  await clearToken();
  redirect("/");
}
