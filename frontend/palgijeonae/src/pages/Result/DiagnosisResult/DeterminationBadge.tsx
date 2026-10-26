import { Determination } from "@/api/product";
import { cn } from "@/lib/cn";

import { DETERMINATION_STYLE } from "./constants";

interface DeterminationBadgeProps {
    determination: Determination
}

function DeterminationBadge({ determination }: DeterminationBadgeProps) {
    const style = DETERMINATION_STYLE[determination];

    return (
        <div className={cn("whitespace-nowrap rounded-full border px-2.5 py-1 text-sm font-semibold", style.className)}>
            {style.label}
        </div>
    );
}

export default DeterminationBadge;
