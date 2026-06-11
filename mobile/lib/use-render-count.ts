import { useEffect, useRef } from "react";
import { devLog } from "./dev-log";

export function useRenderCount(scope: string): void {
  const renderCountRef = useRef(0);
  renderCountRef.current += 1;

  useEffect(() => {
    devLog("render", scope, { renderCount: renderCountRef.current });
  });
}
