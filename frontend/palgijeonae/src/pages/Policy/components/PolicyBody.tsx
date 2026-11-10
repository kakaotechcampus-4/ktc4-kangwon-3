import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import type { PolicyItem, PolicySection, PolicyTable, PolicyTransfer } from "@/pages/Policy/types.ts";

interface PolicyBodyProps {
    sections: PolicySection[]
}

// 데스크톱은 두 열 표, 모바일은 업체명 아래에 업무가 이어지는 세로 배치. 같은 마크업을 CSS로만 바꾼다.
function PolicyTableView({ table }: { table: PolicyTable }) {
    const [companyHeader, taskHeader] = table.headers;

    return (
        <div className="w-full overflow-hidden rounded-lg border border-neutral-line">
            <table className="block w-full text-sm leading-5.25 text-neutral-text md:table">
                <thead className="hidden md:table-header-group">
                    <tr className="border-b border-neutral-line bg-neutral-bg text-neutral-muted">
                        <th scope="col" className="w-1/3 px-4 py-3 text-left font-bold">
                            {companyHeader}
                        </th>
                        <th scope="col" className="px-4 py-3 text-left font-bold">
                            {taskHeader}
                        </th>
                    </tr>
                </thead>
                <tbody className="block md:table-row-group">
                    {table.rows.map(([company, task]) => (
                        <tr key={company} className="flex flex-col gap-0.5 border-b border-neutral-line px-3.5 py-2.5 last:border-b-0 md:table-row md:p-0">
                            <td className="font-bold md:px-4 md:py-3 md:font-normal">{company}</td>
                            <td className="md:px-4 md:py-3">{task}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// 이전받는 자마다 카드 하나. 이름 옆에 전달 경로(via)가 있으면 데스크톱은 가로, 모바일은 세로로 붙인다.
function PolicyTransferList({ transfers }: { transfers: PolicyTransfer[] }) {
    return (
        <ul aria-label="국외 이전을 받는 자" className="flex w-full flex-col gap-3">
            {transfers.map(({ name, via, rows }) => (
                <li key={name} className="flex flex-col gap-2.5 rounded-lg border border-neutral-line bg-neutral-bg p-3.5 md:px-4.5">
                    <div className="flex flex-col gap-0.5 md:flex-row md:items-center md:gap-2">
                        <p className="text-[15px] font-bold text-black">{name}</p>
                        {via && <p className="text-[13px] text-neutral-label">{via}</p>}
                    </div>
                    <dl className="flex flex-col gap-1.5 text-sm leading-5.25">
                        {rows.map(({ label, value }) => (
                            <div key={label} className="flex gap-3">
                                <dt className="w-18 shrink-0 text-neutral-label md:w-24">{label}</dt>
                                <dd className="min-w-0 flex-1 text-neutral-text">{value}</dd>
                            </div>
                        ))}
                    </dl>
                </li>
            ))}
        </ul>
    );
}

function PolicyParagraph({ label, text }: PolicyItem) {
    return (
        <p className="text-sm leading-5.5 whitespace-pre-wrap text-neutral-text md:text-[15px] md:leading-6.5">
            {label && <span className="font-bold text-black">{label}</span>}
            {label && "  "}
            {text}
        </p>
    );
}

function PolicyBody({ sections }: PolicyBodyProps) {
    return (
        <DefaultBox className="gap-6 px-4.5 py-5 md:gap-8 md:p-8">
            {sections.map(({ id, heading, items, table, transfers, trailingItems }) => (
                <section key={id} id={id} className="flex w-full scroll-mt-20 flex-col gap-2 md:scroll-mt-24 md:gap-2.5">
                    <h2 className="text-base leading-6 font-bold text-black md:text-lg md:leading-7">{heading}</h2>
                    {items.map((item) => (
                        <PolicyParagraph key={item.text} {...item} />
                    ))}
                    {table && <PolicyTableView table={table} />}
                    {transfers && <PolicyTransferList transfers={transfers} />}
                    {trailingItems?.map((item) => (
                        <PolicyParagraph key={item.text} {...item} />
                    ))}
                </section>
            ))}
        </DefaultBox>
    );
}

export default PolicyBody;
