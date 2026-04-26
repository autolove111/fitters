export const env = {
  jwtSecret: process.env.JWT_SECRET || "fitters-dev-secret",
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || "7d",
};
