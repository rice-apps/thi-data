export interface AuthService {
  getCurrentUserName(): Promise<string>;
  signOut(): Promise<void>;
}
