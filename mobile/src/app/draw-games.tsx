import { Redirect } from 'expo-router';

export default function DrawPlannerRedirect() {
  return (
    <Redirect
      href={{ pathname: '/lotto', params: { section: 'draw-planner' } }}
    />
  );
}
