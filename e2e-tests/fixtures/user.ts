import { getClient } from "../client";
import { faker } from "@faker-js/faker";

export type User = {
  name: string;
  email: string;
  password?: string;
  language: string;
  accessToken: string;
  refreshToken: string;
};

export async function getTokenAuth(
  email: String,
  password: String
): Promise<User> {
  /**
   * Authenticates an existing user.
   */
  const response: any = await getClient().post("user/token-auth/", {
    email: email,
    password: password,
  });
  return {
    name: response.data.user.first_name,
    email: response.data.user.username,
    language: response.data.user.language,
    accessToken: response.data.access_token,
    refreshToken: response.data.refresh_token,
  };
}

export async function getStaffUser(): Promise<User> {
  /**
   * Authenticates as the 'e2e' staff user. Used in fixtures which rely
   * on API endpoints that require an admin/staff user.
   */
  return getTokenAuth("e2e@baserow.io", "testpassword");
}

export async function createUser(
  skipOnboarding = true,
  skipGuidedTours = true
): Promise<User> {
  const password = faker.internet.password();
  const response: any = await getClient().post("user/", {
    name: faker.name.fullName(),
    email: faker.internet.email(),
    password,
    language: "en",
    authenticate: true,
  });
  const user: User = {
    name: response.data.user.first_name,
    email: response.data.user.username,
    password,
    language: response.data.user.language,
    accessToken: response.data.access_token,
    refreshToken: response.data.refresh_token,
  };
  if (skipOnboarding || skipGuidedTours) {
    await getClient(user).patch("user/account/", {
      completed_onboarding: skipOnboarding,
      completed_guided_tours: skipGuidedTours
        ? ["sidebar", "database", "builder", "automation"]
        : [],
    });
  }
  return user;
}

export async function deleteUser(user: User): Promise<any> {
  await getClient(user).post("user/schedule-account-deletion/");
}
