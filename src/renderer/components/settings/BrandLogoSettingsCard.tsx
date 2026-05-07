type BrandLogoMarkProps = {
  className?: string;
};

export function BrandLogoMark({ className = 'w-8 h-8' }: BrandLogoMarkProps) {
  return (
    <div className={`${className} text-[#2563EB] flex shrink-0 items-center justify-center transition-transform hover:scale-105 duration-300`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full drop-shadow-sm">
        <rect x="3" y="3" width="18" height="18" rx="3.5" />
        <path d="M8 8h8v8H8z" />
        <path d="M12 8v8" />
        <path d="M8 12h8" />
        <circle cx="3" cy="12" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="21" cy="12" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="12" cy="3" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="12" cy="21" r="1.5" fill="currentColor" stroke="none" />
      </svg>
    </div>
  );
}
