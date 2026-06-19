export { default } from "next-auth/middleware";

/**
 * Protect all routes except login and public API paths.
 * Unauthenticated users are automatically redirected to /login.
 */
export const config = {
  matcher: [
    "/dashboard/:path*",
    "/patients/:path*",
    "/assessment/:path*",
    "/analytics/:path*",
    "/settings/:path*",
  ],
};
