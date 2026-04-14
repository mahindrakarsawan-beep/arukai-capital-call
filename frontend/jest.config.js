/** @type {import('jest').Config} */
const config = {
  testEnvironment: "jsdom",
  transform: {
    "^.+\\.(ts|tsx|js|jsx)$": ["babel-jest", { configFile: "./babel.test.config.js" }],
  },
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    // Next.js mocks
    "^next/navigation$": "<rootDir>/src/__mocks__/next/navigation.js",
    "^next/link$": "<rootDir>/src/__mocks__/next/link.js",
    "^next/headers$": "<rootDir>/src/__mocks__/next/headers.js",
    // CSS/asset mocks
    "\\.(css|less|scss|sass)$": "<rootDir>/src/__mocks__/styleMock.js",
    "\\.(jpg|jpeg|png|gif|svg|webp)$": "<rootDir>/src/__mocks__/fileMock.js",
  },
  testMatch: ["**/__tests__/**/*.test.{ts,tsx}", "**/*.test.{ts,tsx}"],
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json"],
  transformIgnorePatterns: ["/node_modules/"],
  globals: {
    "process.env.NEXT_PUBLIC_API_URL": "http://localhost:8000",
  },
};

module.exports = config;
