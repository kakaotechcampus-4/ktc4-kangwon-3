import type { Ref } from "react";

import Process from "./Process";
import { isCorrectableStatus } from "./processStatus";
import type { Agent } from "./useJudgementProcess";

interface AgentProcessItemProps {
    agent: Agent
    onCorrect: () => void
    ref?: Ref<HTMLDivElement>
}

function AgentProcessItem({ agent, onCorrect, ref }: AgentProcessItemProps) {
    return (
        <div ref={ref}>
            <Process
                type={agent.status}
                title={agent.title}
                job={agent.job}
                detail={agent.detail}
                onCorrect={isCorrectableStatus(agent.status) ? onCorrect : undefined}
            />
        </div>
    );
}

export default AgentProcessItem;
