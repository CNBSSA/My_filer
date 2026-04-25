import FilingReviewPage from "@/components/filing-pages/FilingReviewPage";

export function generateStaticParams() {
  return [{ id: "placeholder" }];
}

type Props = { params: Promise<{ id: string }> };

export default async function Page({ params }: Props) {
  const { id } = await params;
  return <FilingReviewPage id={id} />;
}
