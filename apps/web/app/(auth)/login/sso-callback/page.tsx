import { AuthenticateWithRedirectCallback } from "@clerk/nextjs";

export default function LoginSSOCallback() {
  return <AuthenticateWithRedirectCallback />;
}
