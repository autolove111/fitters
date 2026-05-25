export const env = {
  jwtSecret: process.env.JWT_SECRET || "fitters-dev-secret",
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || "7d",
  aiServiceUrl: process.env.AI_SERVICE_URL || "http://health-ai-service:5000",
  aiServiceSecret: process.env.AI_SERVICE_SECRET || "fitters-ai-internal-secret",
};
