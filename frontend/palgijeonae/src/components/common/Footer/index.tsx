import { Fragment, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import logo from '@/assets/logo.svg'
import { CONTACT_EMAIL, FOOTER_NAV_ITEMS, GITHUB_URL, POLICY_LINKS } from '@/constants/navigation'
import { useIsMobile } from '@/hooks/useIsMobile'

const SEPARATOR = (
    <span aria-hidden className="text-box-dashed">
        ·
    </span>
)

function ContactMail() {
    return (
        <span className="whitespace-pre">
            {'문의  '}
            <a href={`mailto:${CONTACT_EMAIL}`} className="underline">
                {CONTACT_EMAIL}
            </a>
        </span>
    )
}

function Footer() {
    // 하단 링크 줄 구성이 데스크톱과 모바일에서 달라서(문의 위치) CSS만으로 나눌 수 없다.
    const isMobile = useIsMobile()

    const policyAndLinks: ReactNode[] = [
        <Link key="terms" to={POLICY_LINKS.terms.to}>
            {POLICY_LINKS.terms.label}
        </Link>,
        <Link key="privacy" to={POLICY_LINKS.privacy.to} className="font-bold text-neutral-text">
            {POLICY_LINKS.privacy.label}
        </Link>,
        ...(isMobile ? [] : [<ContactMail key="contact" />]),
        <a key="github" href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            GitHub
        </a>,
    ]

    return (
        <footer className="border-t border-neutral-line bg-white">
            <div className="mx-auto flex w-full max-w-297 flex-col gap-5 px-5 pt-8 pb-10 md:w-3/5 md:min-w-150 md:gap-6 md:px-0 md:pt-10 md:pb-12">
                <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
                    <div className="flex flex-col gap-2 md:gap-2.5">
                        <img src={logo} alt="" className="h-8 w-24 object-contain object-left md:h-10 md:w-30" />
                        <p className="text-[13px] leading-4.75 text-neutral-muted md:text-sm md:leading-5">
                            구매대행·사입 상품의 국내 법령 요건을 AI가 확인해요
                        </p>
                    </div>
                    <nav aria-label="푸터 메뉴">
                        <ul className="flex gap-5 text-sm font-medium text-neutral-text md:gap-6">
                            {FOOTER_NAV_ITEMS.map(({ label, to }) => (
                                <li key={to}>
                                    <Link to={to}>{label}</Link>
                                </li>
                            ))}
                        </ul>
                    </nav>
                </div>
                <hr className="w-full border-neutral-line" />
                <div className="flex flex-col gap-1.5 text-xs leading-4.5 text-neutral-label md:gap-1 md:text-[13px] md:leading-5">
                    <p>국가법령정보센터·관세청 등이 공개한 법령과 고시를 기준으로 확인하며, 법령 개정은 매일 반영합니다.</p>
                    <p>진단 결과는 참고용 자료이며 행정기관의 공식 해석이나 법률 자문을 대신하지 않습니다. 최종 법령 준수 책임은 판매자에게 있습니다.</p>
                </div>
                <div className="flex flex-col gap-5 text-xs md:flex-row md:items-center md:justify-between md:gap-0 md:text-[13px]">
                    <ul className="flex flex-wrap items-center gap-x-1.5 text-neutral-muted md:gap-x-2">
                        {policyAndLinks.map((item, index) => (
                            <Fragment key={index}>
                                {index > 0 && <li aria-hidden>{SEPARATOR}</li>}
                                <li>{item}</li>
                            </Fragment>
                        ))}
                    </ul>
                    {isMobile && (
                        <p className="text-neutral-muted">
                            <ContactMail />
                        </p>
                    )}
                    <p className="text-neutral-border">© 2026 팔기전에 · 카카오테크 캠퍼스 4기 강원대 3팀</p>
                </div>
            </div>
        </footer>
    )
}

export default Footer
