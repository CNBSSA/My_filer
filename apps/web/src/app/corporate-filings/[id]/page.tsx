import CorporateFilingReviewPage from "@/components/filing-pages/CorporateFilingReviewPage";

export function generateStaticParams() {
  return [{ id: "placeholder" }];
}

type Props = { params: Promise<{ id: string }> };

export default async function Page({ params }: Props) {
  const { id } = await params;
  return <CorporateFilingReviewPage id={id} />;
}
