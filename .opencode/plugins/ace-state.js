export const AceStatePlugin = async (ctx) => {
  return {
    "session.created": async (input, output) => {
      // Auto-inject live repo state when a session starts in this project.
      // No manual --write or --brief needed from the owner.
      try {
        const { $ } = await import("bun");
        const dir = input.session?.directory
          || ctx.directory
          || "C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1";
        const proc = Bun.spawnSync(
          ["python", "tools/ace_state.py", "--brief", "W1-rights-scope"],
          { cwd: dir },
        );
        const brief = proc.stdout ? proc.stdout.toString().slice(0, 1500) : "";
        output.context = output.context || [];
        output.context.push(
          `## ACE live state (auto-injected, do not research)\n`
          + `Repo root: ${dir}\n`
          + `Read docs/coordinator/STATE.json first, then the task packet.\n`
          + (brief ? `\n${brief}` : ""),
        );
      } catch (e) {
        // Never block session start on state injection failure.
      }
    },
    "tool.execute.after": async (input, output) => {
      // Refresh STATE.json + PROGRESS.md after any file edit, so the next
      // dispatch sees fresh facts without the owner running --write.
      try {
        if (input.tool !== "edit" && input.tool !== "write") return;
        const dir = ctx.directory
          || "C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1";
        const { spawnSync } = await import("child_process");
        spawnSync("python", ["tools/ace_state.py", "--write"], { cwd: dir });
      } catch (e) {
        // Silent: state refresh must never break the worker.
      }
    },
    "experimental.session.compacting": async (input, output) => {
      // Keep task truth across compaction: re-anchor to STATE.json.
      output.context = output.context || [];
      output.context.push(
        `## ACE compaction anchor\n`
        + `After compaction, read docs/coordinator/STATE.json before any edit. `
        + `Packets in docs/coordinator/tasks/<ID>/packet.md are the only orders. `
        + `Never re-derive git state or contracts from chat history.`,
      );
    },
  };
};
