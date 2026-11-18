import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

const advisoryUrl = "https://github.com/advisories/GHSA-fc5q-39xc-vjpf";
const audit = spawnSync(
  process.execPath,
  [process.env.npm_execpath, "audit", "--audit-level=high", "--json"],
  { encoding: "utf8", stderr: "inherit" },
);

function printReport() {
  if (audit.stdout) process.stdout.write(audit.stdout);
  if (audit.error) console.error(audit.error.message);
}

function canAllow(report, packages) {
  if (report.auditReportVersion !== 2 || report.error || !report.vulnerabilities) {
    return false;
  }

  const findings = report.vulnerabilities;
  const blocking = Object.values(findings).filter(({ severity }) =>
    ["high", "critical"].includes(severity),
  );
  const totals = report.metadata?.vulnerabilities;
  if (totals?.critical !== 0 || !blocking.length || blocking.length !== totals.high) return false;

  // Quitar la excepción cuando haya una versión corregida. Cada ruta afectada
  // debe ser exclusiva de desarrollo y llegar únicamente a este aviso.
  function onlyKnownAdvisory(name, chain = new Set()) {
    const finding = findings[name];
    if (chain.has(name) || !finding?.nodes?.length || !finding.via?.length) return false;
    if (finding.nodes.some((path) => packages[path]?.dev !== true)) return false;
    if (name === "picomatch" && finding.nodes.some((path) => packages[path].version !== "4.0.7")) {
      return false;
    }

    const nextChain = new Set(chain).add(name);
    return finding.via.every((cause) => {
      if (typeof cause === "string") return onlyKnownAdvisory(cause, nextChain);
      return name === "picomatch" && cause?.name === name && cause.url === advisoryUrl;
    });
  }

  return blocking.every(({ name }) => onlyKnownAdvisory(name));
}

if (audit.status === 0) {
  printReport();
} else {
  let allowed = false;
  if (audit.status === 1) {
    try {
      const lockfile = JSON.parse(readFileSync(new URL("../package-lock.json", import.meta.url)));
      allowed = canAllow(JSON.parse(audit.stdout), lockfile.packages);
    } catch (error) {
      console.error(`No se pudo verificar el informe de npm audit. ${error.message}`);
    }
  }
  printReport();
  if (allowed) {
    console.warn(
      `Excepción temporal de CI para picomatch 4.0.7, solo en desarrollo. ${advisoryUrl}`,
    );
  } else {
    process.exitCode = 1;
  }
}
