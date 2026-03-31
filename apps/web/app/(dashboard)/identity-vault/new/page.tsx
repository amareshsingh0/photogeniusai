// Force dynamic rendering to prevent Clerk errors during CI builds
export const dynamic = 'force-dynamic'

import NewIdentityClient from "./NewIdentityClient"

export default function NewIdentityPage() {
  return <NewIdentityClient />
}
