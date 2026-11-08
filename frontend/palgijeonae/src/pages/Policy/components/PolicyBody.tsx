import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import type { PolicySection, PolicyTable } from "@/pages/Policy/types.ts";

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

function PolicyBody({ sections }: PolicyBodyProps) {
    return (
        <DefaultBox className="gap-6 px-4.5 py-5 md:gap-8 md:p-8">
            {sections.map(({ id, heading, items, table }) => (
                <section key={id} id={id} className="flex w-full scroll-mt-20 flex-col gap-2 md:scroll-mt-24 md:gap-2.5">
                    <h2 className="text-base leading-6 font-bold text-black md:text-lg md:leading-7">{heading}</h2>
                    {items.map(({ label, text }) => (
                        <p key={text} className="text-sm leading-5.5 wrap-break-word whitespace-pre-wrap text-neutral-text md:text-[15px] md:leading-6.5">
                            {label && <span className="font-bold text-black">{label}</span>}
                            {label && "  "}
                            {text}
                        </p>
                    ))}
                    {table && <PolicyTableView table={table} />}
                </section>
            ))}
        </DefaultBox>
    );
}

export default PolicyBody;
