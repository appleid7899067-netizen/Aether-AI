import type { NextConfig } from "next";
import { baseURL } from "./lib/base-url";

const nextConfig: NextConfig = {
  // ChatGPT loads the widget inside an iframe: static assets must resolve
  // against this deployment, not against the iframe's origin.
  assetPrefix: baseURL,
};

export default nextConfig;
