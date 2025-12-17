import { loginResult } from '@/utils/checklogin';
import { redirect } from 'next/navigation';

export default async function Home() {
    const user = await loginResult();

    if (!user) {
        redirect("/login");
    }

    // If logged in, redirect to the main dashboard
    redirect("/homescreen");
}