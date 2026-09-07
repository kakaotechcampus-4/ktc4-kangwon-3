interface InformationCardProps {
    image: string
    title: string
    description: string
}

function InformationCard({ image, title, description }: InformationCardProps) {
    return (
        <div className="flex w-full flex-col gap-6 rounded-[30px] bg-[#E7EEFB] px-8 py-7">
            <div className="flex items-center gap-5">
                <img src={image} alt={title} className="h-[50px] w-[50px] shrink-0 object-contain" />
                <h3 className="text-2xl font-semibold text-black">{title}</h3>
            </div>
            <p className="text-xl leading-[1.5] tracking-[0.05em] text-neutral-text">
                {description}
            </p>
        </div>
    );
}

export default InformationCard;