"use client";

import { useState } from "react";
import Link from "next/link";
import type { TargetResponse } from "../../lib/types";
import { VerificationPanel } from "./VerificationPanel";

export function TargetRow({
  target,
  onVerified,
}: {
  target: TargetResponse;
  onVerified: (target: TargetResponse) => void;
}) {
  const [showVerification, setShowVerification] = useState(false);
  const isActive = target.verification_status === "active";

  return (
    <li className="rounded-lg border border-black/10 dark:border-white/20 p-4 text-sm space-y-1">
      <div className="flex items-center justify-between">
        <span className="break-all">{target.origin}</span>
        {isActive ? (
          <span className="text-xs text-severity-pass">Verified</span>
        ) : (
          <span className="text-xs text-black/50 dark:text-white/50">Unverified</span>
        )}
      </div>

      <div className="flex items-center gap-4 text-xs pt-1">
        <Link
          href={`/targets/${target.target_id}/monitoring`}
          className="underline underline-offset-2"
        >
          Monitoring
        </Link>
        {!isActive ? (
          <button
            type="button"
            onClick={() => setShowVerification((value) => !value)}
            className="underline underline-offset-2"
          >
            {showVerification ? "Hide verification" : "Verify ownership"}
          </button>
        ) : null}
      </div>

      {!isActive && showVerification ? (
        <VerificationPanel
          targetId={target.target_id}
          onVerified={(updated) => {
            onVerified(updated);
            setShowVerification(false);
          }}
        />
      ) : null}
    </li>
  );
}
