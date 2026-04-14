const useRouter = jest.fn(() => ({
  push: jest.fn(),
  replace: jest.fn(),
  prefetch: jest.fn(),
  back: jest.fn(),
  forward: jest.fn(),
  refresh: jest.fn(),
}));

const usePathname = jest.fn(() => "/");
const useSearchParams = jest.fn(() => new URLSearchParams());
const redirect = jest.fn();
const notFound = jest.fn();

module.exports = {
  useRouter,
  usePathname,
  useSearchParams,
  redirect,
  notFound,
};
