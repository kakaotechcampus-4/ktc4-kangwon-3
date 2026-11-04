import { cn } from "@/lib/cn";

interface AgentCardProps {
    icon: string
    name: string
    description: string
    reverse: boolean
}

function AgentCard({ icon, name, description, reverse }: AgentCardProps) {
    return (
        <div className={cn("flex items-center gap-8", reverse && "flex-row-reverse")}>
            <img src={icon} alt="" className="h-20 w-20 shrink-0" />
            <div className="flex flex-col gap-1.5">
                <h3 className="text-xl font-semibold text-black">{name}</h3>
                <p className="text-base leading-relaxed text-neutral-text">{description}</p>
            </div>
        </div>
    );
}

export default AgentCard;
