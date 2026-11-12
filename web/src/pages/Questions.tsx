import { CopyButton, Citations, Empty, PageIntro } from "../components";
import type { DossierSnapshotResponse as Dossier } from "../contracts";
export function Questions({ data }: { data: Dossier }) {
  const roles = ["SELLER", "AGENT", "SYNDIC", "NOTARY"];
  return (
    <>
      <PageIntro
        title="A better conversation starts here"
        description="Specific questions based on the available information. Copy them for your next conversation."
      />
      {data.questions.length ? (
        <>
          <div className="section-heading">
            <span>{data.questions.length} questions to clarify</span>
            <CopyButton
              text={data.questions
                .map(
                  (q) =>
                    `${q.target_role}: ${q.question_text}\nWhy: ${q.reason}`,
                )
                .join("\n\n")}
            >
              Copy all questions
            </CopyButton>
          </div>
          {roles
            .filter((role) =>
              data.questions.some((q) => q.target_role === role),
            )
            .map((role) => (
              <section key={role}>
                <h2 className="group-title">Ask the {role.toLowerCase()}</h2>
                {data.questions
                  .filter((q) => q.target_role === role)
                  .map((q) => (
                    <article className="panel question" key={q.key}>
                      <h3>{q.question_text}</h3>
                      <p>
                        <strong>Why:</strong> {q.reason}
                      </p>
                      <Citations sources={q.sources} wid={data.workspace.id} />
                      <CopyButton text={q.question_text}>
                        Copy question
                      </CopyButton>
                    </article>
                  ))}
              </section>
            ))}
        </>
      ) : (
        <Empty
          title="No questions yet"
          text="Questions appear when the available information reveals an open point or missing information."
        />
      )}
    </>
  );
}
