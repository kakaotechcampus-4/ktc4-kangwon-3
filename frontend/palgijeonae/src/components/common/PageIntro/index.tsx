interface PageIntroProps {
    title: string
    description: string
}

function PageIntro({ title, description }: PageIntroProps) {
    return (
        <div className="flex flex-col items-start gap-2">
            <h1 className="text-3xl font-bold leading-12 text-center text-black">{title}</h1>
            <p className="text-xl leading-8.75 text-neutral-text">{description}</p>
        </div>
    );
}

export default PageIntro;
