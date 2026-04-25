import NgoFilingReviewPage from "@/components/filing-pages/NgoFilingReviewPage";

export function generateStaticParams() {
  return [{ id: "placeholder" }];
}

type Props = { params: Promise<{ id: string }> };

export default async function Page({ params }: Props) {
  const { id } = await params;
  return <NgoFilingReviewPage id={id} />;
}
