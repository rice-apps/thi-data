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
    const data = await getData();

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <h1 className="mt-4 text-2xl bg-black-100 p-4 rounded-lg">
                {data.message}
            </h1>
        </main>
    );
}