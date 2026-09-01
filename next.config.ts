import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The collector's address must never reach the browser. Every fetch of it
  // happens in a server component or a route handler, exactly as GEXYGEN keeps
  // its compute service off the client — here the reason is not a licence but
  // the same principle: the browser has no business knowing the shape of the
  // machine's private network.
  env: {},
  eslint: { ignoreDuringBuilds: false },
};

export default nextConfig;
