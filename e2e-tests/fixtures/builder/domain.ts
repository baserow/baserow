import { getClient } from "../../client";
import { Builder } from "./builder";

export class PublishedBuilder {
  constructor(
    public id: number,
    // Path of the first non-shared page, e.g. "/page".
    public pagePath: string,
    // The published copy of the user source (its id differs from the editor's).
    public userSourceId: number,
  ) {}

  // URL path of the preview route that renders the published, visibility
  // filtered page without needing a real domain to resolve.
  previewPath(): string {
    return `/builder/${this.id}/preview${this.pagePath}`;
  }
}

/**
 * Creates a custom domain for the builder, publishes it (waiting for the async
 * job to finish), and returns the resulting published builder details.
 */
export async function publishBuilder(
  builder: Builder,
  domainName: string,
): Promise<PublishedBuilder> {
  const client = getClient(builder.workspace.user);

  const domain: any = await client.post(`builder/${builder.id}/domains/`, {
    type: "custom",
    domain_name: domainName,
  });

  const job: any = await client.post(
    `builder/domains/${domain.data.id}/publish/async/`,
    {},
  );

  // Poll the publish job until it finishes.
  let state = job.data.state;
  for (let i = 0; i < 60 && state !== "finished"; i++) {
    const poll: any = await client.get(`jobs/${job.data.id}/`);
    state = poll.data.state;
    if (state === "failed") {
      throw new Error(
        `Publish job failed: ${poll.data.human_readable_error || ""}`,
      );
    }
    if (state !== "finished") {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  if (state !== "finished") {
    throw new Error("Publish job did not finish in time");
  }

  const published: any = await client.get(
    `builder/domains/published/by_name/${domainName}/`,
  );
  const page = published.data.pages.find((p: any) => p.path !== "__shared__");
  const userSource = published.data.user_sources[0];

  return new PublishedBuilder(published.data.id, page.path, userSource.id);
}
