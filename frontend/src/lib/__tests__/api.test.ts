/**
 * api.ts tests — A2 (POR-147 / ARU-17-A2)
 * Tests: attestPackage, claimPackage, releasePackage, transitionPackage functions.
 * Mocks fetch and verifies correct endpoint + body.
 */

import {
  attestPackage,
  claimPackage,
  releasePackage,
  transitionPackage,
} from "@/lib/api";

const TOKEN = "test-jwt-token";
const PKG_ID = "pkg-001";

global.fetch = jest.fn();

function mockFetchOk(body: unknown = {}) {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => body,
  });
}

function mockFetchFail(status = 400, detail = "Bad request") {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    status,
    json: async () => ({ detail }),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("attestPackage", () => {
  it("posts to /packages/{id}/attest with approved action", async () => {
    mockFetchOk({ id: PKG_ID, state: "decision_recorded" });
    await attestPackage(PKG_ID, "approved", "Looks good", TOKEN);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/packages/${PKG_ID}/attest`),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({ action: "approved", note: "Looks good" }),
      })
    );
  });

  it("posts to /packages/{id}/attest with rejected action", async () => {
    mockFetchOk({ id: PKG_ID, state: "decision_recorded" });
    await attestPackage(PKG_ID, "rejected", "Issues found", TOKEN);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/packages/${PKG_ID}/attest`),
      expect.objectContaining({
        body: JSON.stringify({ action: "rejected", note: "Issues found" }),
      })
    );
  });

  it("throws on non-ok response", async () => {
    mockFetchFail(403, "Forbidden");
    await expect(attestPackage(PKG_ID, "approved", "", TOKEN)).rejects.toThrow(
      "Forbidden"
    );
  });
});

describe("claimPackage", () => {
  it("posts to /packages/{id}/claim", async () => {
    mockFetchOk({});
    await claimPackage(PKG_ID, TOKEN);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/packages/${PKG_ID}/claim`),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      })
    );
  });

  it("throws on non-ok response", async () => {
    mockFetchFail(409, "Already claimed");
    await expect(claimPackage(PKG_ID, TOKEN)).rejects.toThrow("Already claimed");
  });
});

describe("releasePackage", () => {
  it("posts to /packages/{id}/release", async () => {
    mockFetchOk({});
    await releasePackage(PKG_ID, TOKEN);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/packages/${PKG_ID}/release`),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: `Bearer ${TOKEN}`,
        }),
      })
    );
  });

  it("throws on non-ok response", async () => {
    mockFetchFail(403, "Not the claimant");
    await expect(releasePackage(PKG_ID, TOKEN)).rejects.toThrow("Not the claimant");
  });
});

describe("transitionPackage", () => {
  it("posts to /packages/{id}/transition with next_state", async () => {
    mockFetchOk({});
    await transitionPackage(PKG_ID, "routed_for_approval", TOKEN);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/packages/${PKG_ID}/transition`),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ next_state: "routed_for_approval" }),
      })
    );
  });

  it("includes optional reason when provided", async () => {
    mockFetchOk({});
    await transitionPackage(PKG_ID, "under_review", TOKEN, "Returning for revision");
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/packages/${PKG_ID}/transition`),
      expect.objectContaining({
        body: JSON.stringify({
          next_state: "under_review",
          reason: "Returning for revision",
        }),
      })
    );
  });

  it("throws on 409 invalid transition", async () => {
    mockFetchFail(409, "Transition routed_for_approval→submitted not permitted");
    await expect(
      transitionPackage(PKG_ID, "submitted", TOKEN)
    ).rejects.toThrow(/not permitted/i);
  });
});
