'use server';

import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { APIError } from 'better-auth/api';
import { auth } from '@/lib/auth';

export async function signOutAction() {
  await auth.api.signOut({ headers: await headers() });
  redirect('/login');
}

export async function signInAction(formData: FormData) {
  const email = formData.get('email') as string;
  const password = formData.get('password') as string;

  try {
    await auth.api.signInEmail({
      body: { email, password },
      headers: await headers(),
    });
  } catch (error) {
    if (error instanceof APIError) {
      return { error: error.message };
    }
    throw error;
  }

  redirect('/homescreen');
}

export async function signUpAction(formData: FormData) {
  const email = formData.get('email') as string;
  const password = formData.get('password') as string;
  const firstName = formData.get('firstName') as string;
  const lastName = formData.get('lastName') as string;

  try {
    await auth.api.signUpEmail({
      body: {
        email,
        password,
        name: `${firstName} ${lastName}`.trim(),
      },
      headers: await headers(),
    });
  } catch (error) {
    if (error instanceof APIError) {
      const isPasswordError = /password/i.test(error.message);
      const isEmailError = /email/i.test(error.message);
      return {
        error: error.message,
        values: {
          firstName,
          lastName,
          email: isEmailError ? '' : email,
          password: isPasswordError ? '' : password,
        },
      };
    }
    throw error;
  }

  redirect('/homescreen');
}
