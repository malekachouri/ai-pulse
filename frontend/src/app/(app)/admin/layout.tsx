import { AdminNav } from "@/components/admin/admin-shell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AdminNav />
      {children}
    </>
  );
}
