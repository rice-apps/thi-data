import { createClient } from '@/utils/supabase/server';
import { redirect } from 'next/navigation';

async function getData() {
    try {
        const res = await fetch('http://localhost:8000/api/data', {
            cache: 'no-store'
        });

        if (!res.ok) {
            throw new Error('Failed to fetch data');
        }

        return res.json();
    } catch (error) {
        console.error("Error fetching data:", error);
        return {message: "Failed to load data from backend."};
    }
}

export default async function Home() {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    
    // Middleware handles authentication, but we still check for safety
    if (!user) {
        redirect('/login');
    }
    
    // const data = await getData();

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <h1 className="mt-4 text-2xl bg-black-100 p-4 rounded-lg">
                Home page
            </h1>

            <div className="mt-6">
                <p className="text-green-600 mb-4">Logged in as: {user.email}</p>
                <form action="/signout" method="post">
                    <button
                        type="submit"
                        className="bg-red-500 text-white p-2 rounded hover:bg-red-600 transition"
                    >
                        Sign Out
                    </button>
                </form>
            </div>
        </main>
    )
}