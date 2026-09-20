export function ErrorScreen({ title, detail }: { title: string; detail: string }) {
  return (
    <section className="notice" role="alert">
      <h1>{title}</h1>
      <p>{detail}</p>
    </section>
  );
}

export function NotFound({ what }: { what: string }) {
  return (
    <section className="notice">
      <h1>Not found</h1>
      <p>{what}</p>
      <p>
        <a className="button" href="#/">
          Back to all products
        </a>
      </p>
    </section>
  );
}
