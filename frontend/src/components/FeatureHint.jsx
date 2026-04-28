import React from 'react';
import { HelpCircle } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from './ui/tooltip';

/**
 * Inline contextual help icon.
 * Wraps shadcn Tooltip with a brand-styled "?" trigger.
 *
 * Usage:
 *   <FeatureHint id="wizard">Choisis parmi 35+ templates...</FeatureHint>
 */
export default function FeatureHint({ id, children, side = 'top' }) {
  const testId = id ? `feature-hint-${id}` : 'feature-hint';
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            data-testid={testId}
            aria-label="Aide"
            className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-white/5 hover:bg-[#E4FF00]/20 hover:text-[#E4FF00] text-white/60 transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <HelpCircle className="w-3.5 h-3.5" strokeWidth={2.2} />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-[260px] bg-[#0F0F13] text-white border-white/10 backdrop-blur-xl text-xs font-['IBM_Plex_Sans']"
        >
          {children}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
