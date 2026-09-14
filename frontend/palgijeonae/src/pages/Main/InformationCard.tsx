interface InformationCardProps {
    image: string
    title: string
    description: string
}

function InformationCard({ image, title, description }: InformationCardProps) {
    return (
        <div className="flex w-full flex-1 flex-col gap-4.5 rounded-3xl bg-[#E7EEFB] px-6 py-6">
            <div className="flex items-center gap-3.75">
                <img src={image} alt={title} className="h-8 w-8 shrink-0 object-contain" />
                <h3 className="text-lg font-semibold text-black">{title}</h3>
            </div>
            <p className="text-[15px] leading-normal tracking-wider text-neutral-text">
                {description}
            </p>
        </div>
    );
}

export default InformationCard;