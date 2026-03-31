import { AuthenticateWithRedirectCallback } from "@clerk/nextjs";

export default function SignupSSOCallback() {
  return <AuthenticateWithRedirectCallback />;
}
