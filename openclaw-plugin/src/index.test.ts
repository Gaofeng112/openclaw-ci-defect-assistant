import { describe, expect, it } from "vitest";
import entry from "./index.js";
import { getToolPluginMetadata } from "openclaw/plugin-sdk/tool-plugin";

describe("openclaw-ci-defect-assistant", () => {
  it("declares tool metadata", () => {
    const metadata = getToolPluginMetadata(entry);
    expect(metadata?.tools.map((tool) => tool.name)).toEqual(["ci_defect_assistant_chat"]);
    expect(metadata?.tools[0]?.description).toContain("Teambition");
    expect(metadata?.tools[0]?.description).toContain("缺陷");
    expect(metadata?.tools[0]?.description).toContain("skill_workshop");
  });
});
