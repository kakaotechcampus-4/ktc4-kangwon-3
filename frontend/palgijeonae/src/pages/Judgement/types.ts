export enum ProcessType {
    Call = "call",
    Act = "act",
    End = "end",
    Skip = "skip",
    Fail = "fail"
}

export interface Agent {
    id: string
    title: string
    job: string
    detail: string
    status: ProcessType
}